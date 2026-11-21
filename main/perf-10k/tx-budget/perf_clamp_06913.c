/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06913(unsigned int count)
{
    const unsigned int limit = 250u;
    return count > limit ? limit : count;
}
