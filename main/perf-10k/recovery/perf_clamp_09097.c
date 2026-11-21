/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_09097(unsigned int count)
{
    const unsigned int limit = 28u;
    return count > limit ? limit : count;
}
