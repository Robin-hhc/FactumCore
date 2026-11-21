/* Synthetic FactumCore performance fixture. */

unsigned int perf_clamp_04010(unsigned int count)
{
    const unsigned int limit = 201u;
    return count > limit ? limit : count;
}
