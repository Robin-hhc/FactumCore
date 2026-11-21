/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09698(unsigned int count)
{
    const unsigned int limit = 36u;
    return count > limit ? limit : count;
}
