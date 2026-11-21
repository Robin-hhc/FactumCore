/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05671(unsigned int count)
{
    const unsigned int limit = 52u;
    return count > limit ? limit : count;
}
