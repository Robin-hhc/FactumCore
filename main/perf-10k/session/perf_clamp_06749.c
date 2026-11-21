/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_06749(unsigned int count)
{
    const unsigned int limit = 201u;
    return count > limit ? limit : count;
}
