/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_08870(unsigned int count)
{
    const unsigned int limit = 153u;
    return count > limit ? limit : count;
}
