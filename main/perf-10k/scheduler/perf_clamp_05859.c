/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_05859(unsigned int count)
{
    const unsigned int limit = 11u;
    return count > limit ? limit : count;
}
