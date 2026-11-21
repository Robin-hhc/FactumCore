/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_01834(unsigned int count)
{
    const unsigned int limit = 61u;
    return count > limit ? limit : count;
}
